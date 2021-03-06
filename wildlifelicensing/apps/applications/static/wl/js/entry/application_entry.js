define(['jQuery', 'handlebars.runtime', 'parsley', 'bootstrap', 'bootstrap-datetimepicker',
        'js/handlebars_helpers', 'js/precompiled_handlebars_templates'], function($, Handlebars) {
    function _layoutItem(item, index, isRepeat, itemData) {
        var itemContainer = $('<div>');

        if(item.type == 'section') {
            item.index = index;
        }

        // if this is a repeatable item (such as a group), add repetitionIndex to item ID
        if(item.isRepeatable) {
        	item.isRemovable = isRepeat;
        }

        if(itemData != undefined && item.name in itemData) {
            item.value = itemData[item.name];
        }

        itemContainer.append(Handlebars.templates[item.type](item));

        // unset item value if they were set otherwise there may be unintended consequences if extra form fields are created dynamically
        item.value = undefined;

        if(item.children !== undefined) {
            var childrenAnchorPoint;

            // if no children anchor point was defined within the template, create one under current item
            if(itemContainer.find('.children-anchor-point').length) {
                childrenAnchorPoint = itemContainer.find('.children-anchor-point');
            } else {
                childrenAnchorPoint = $('<div>');
                childrenAnchorPoint.addClass('children-anchor-point');
                itemContainer.append(childrenAnchorPoint);
            }

            if(item.condition !== undefined) {
                var inputSelector = itemContainer.find('input, select');

                // hide children initially if current item value does not equal condition
                if(inputSelector.val() !== item.condition) {
                    childrenAnchorPoint.hide();
                }

                inputSelector.change(function(e) {
                    if ($(this).val() === item.condition) {
                        childrenAnchorPoint.slideDown('medium');
                    } else {
                        childrenAnchorPoint.slideUp('medium');
                    }
                });
            }

            $.each(item.children, function(childIndex, child) {
                if(child.isRepeatable) {
                    var childData;
                    if(itemData !== undefined) {
                        childData = itemData[child.name][0];
                    }
                    childrenAnchorPoint.append(_layoutItem(child, childIndex, false, childData));

                    var repeatItemsAnchorPoint = $('<div>');
                    childrenAnchorPoint.append(repeatItemsAnchorPoint);

                    var addGroupDiv = $('<div>').addClass('add-group');
                    var addGroupLink = $('<a>').text('Add ' + child.label, itemData);
                    addGroupLink.click(function(e) {
                        repeatItem = _layoutItem(child, childIndex, true, itemData);
                        repeatItem.find('.hidden').removeClass('hidden');
                        repeatItemsAnchorPoint.append(repeatItem);
                    });
                    childrenAnchorPoint.append(addGroupDiv.append(addGroupLink));

                    if(itemData != undefined && child.name in itemData && itemData[child.name].length > 1) {
                        $.each(itemData[child.name].slice(1), function(childRepetitionIndex, repeatData) {
                            repeatItemsAnchorPoint.append(_layoutItem(child, index, true, repeatData));
                        });
                    }
                } else {
                    childrenAnchorPoint.append(_layoutItem(child, childIndex, false, itemData));
                }
            });
        }

        if(item.isRepeatable) {
            _setupCopyRemoveEvents(item, itemContainer, index, true);
        }

        return itemContainer;
    }

    function _setupCopyRemoveEvents(item, itemSelector, index, isRepeat) {
    	itemSelector.find('.copy').click(function(e) {
            var itemCopy = _layoutItem(item, index, true);

            itemSelector.find('input, select').each(function() {
                inputCopy = itemCopy.find("[name='" + $(this).attr('name') + "']");
                inputCopy.val($(this).val());

                if(!$(this).parent().parent().find('.children-anchor-point').is(':hidden')) {
                    inputCopy.parent().parent().find('.children-anchor-point').show();
                }
            });
            itemCopy.find('.hidden').removeClass('hidden');
            itemSelector.after(itemCopy);
            _setupCopyRemoveEvents(item, itemCopy, index, true);
        });

        itemSelector.find('.remove').click(function(e) {
            itemSelector.remove();
        });

        // initialise all datapickers
    	itemSelector.find('.date').datetimepicker({
            format: 'DD/MM/YYYY'
        });
    }

    return {
        layoutFormItems: function(formContainerSelector, formStructure, data) {
            var formContainer = $(formContainerSelector);

            $.each(formStructure, function(index, item) {
                formContainer.append(_layoutItem(item, index, false, data));
            });

            // initialise all datapickers
            $('.date').datetimepicker({
                format: 'DD/MM/YYYY'
            });

            // initialise parsley form validation
            $('form').parsley({
                successClass: "has-success",
                errorClass: "has-error",
                classHandler: function(el) {
                    return el.$element.closest(".form-group");
                },
                errorsContainer: function(el) {
                    return el.$element.parents('.form-group');
                },
                errorsWrapper: '<span class="help-block">',
                errorTemplate: '<div></div>'
            }).on('field:validate', function(el) {
                // skip validation of invisible fields
                if (!el.$element.is(':visible')) {
                    el.value = false;
                    return true;
                }
            });
        },
        initialiseSidebarMenu: function(sidebarMenuSelector) {
            $('.section').each(function(index, value) {
                var link = $('<a>');
                link.attr('href', '#section-' + index);
                link.text($(this).text());
                $('#sectionList ul').append($('<li>').append(link));
            });

            var sectionList = $(sidebarMenuSelector);
            $('body').scrollspy({ target: '#sectionList' });
            sectionList.affix({ offset: { top: sectionList.offset().top }});
        }
    }
});