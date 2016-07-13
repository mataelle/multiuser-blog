 $(document).ready(function(){

    // methods for modal message - edit and delete buttons
    $('.not-allowed').on('click', function(e){
        e.preventDefault();
        $('#not-allowed').toggleClass('fade');
        $('#not-allowed').css('display', $('#not-allowed').css('display') == 'block' ? 'none' : 'block');
    });
    $('#close-modal').on('click', function(e) {
        $('#not-allowed').toggleClass('fade');
        $('#not-allowed').css('display', $('#not-allowed').css('display') == 'block' ? 'none' : 'block');
    });

    // methods for modal message - like button
    $('.not-allowed-like').on('click', function(e){
        e.preventDefault();
        $('#not-allowed-like').toggleClass('fade');
        $('#not-allowed-like').css('display', $('#not-allowed-like').css('display') == 'block' ? 'none' : 'block');
    });
    $('#close-modal-like').on('click', function(e) {
        $('#not-allowed-like').toggleClass('fade');
        $('#not-allowed-like').css('display', $('#not-allowed-like').css('display') == 'block' ? 'none' : 'block');
    });

 });

// process like action
function Like(object, post_id){
    if (! $(object).hasClass('not-allowed-like')) {
        $.ajax({
            url: '/blog/' + post_id + '/like',
            type: 'POST',
            data: { 'post_id' : post_id },
            success: function (data) {
                $(object).text('Liked');
            },
            error: function (data) {
                console.log("Something went wrong...");
            },
        });
    }
};

// opens form that allows edit comment
function openEditCommentForm(object){
    $($(object).parent().parent().find('form')).css('display', 'block');
    $($(object).parent()).css('display', 'none');
};

// closes form allowing edit comment
function closeEditCommentForm(object){
    $($(object).parent().parent().parent()).css('display', 'none');
    $($(object).parent().parent().parent().find('.err_msg')).css('display', 'none');
    $($(object).parent().parent().parent().parent().find('.comment-body')).css('display', 'block');
};

// processing creation of new comment
function addComment(object, post_id){
    // get comment text, check that it's not empty
    var comment = $($(object).parent().parent().parent().find('textarea'))[0].value;
    $($(object).parent().parent().parent().find('textarea'))[0].value = '';
    if (comment.length == 0) {
        $($(object).parent().parent().parent().find('.err_msg')).css('display', 'block');
    }
    else {
        $.ajax({
            url: '/blog/' + post_id + '/comment',
            type: 'POST',
            data: {
                'post_id' : post_id,
                 'comment' : comment
             },
            success: function (data) {
                // try find error message
                try {
                    if (JSON.parse(data)['err_msg'] != undefined) {
                        $($(object).parent().parent().parent().find('.err_msg')).css('display', 'block');
                    }
                }
                // if there is no error messages, insert recieved data where needed
                catch (e) {
                    $(data).insertBefore($($(object).parent().parent().parent().parent().find('hr')));
                }
            },
            error: function (data) {
                console.log("Something went wrong...");
            },
        });
        $($(object).parent().parent().parent().find('.err_msg')).css('display', 'none');
    }
};

// process comment editing
function editComment(object, comment_id){
    // get comment text, check that it's not empty
    var comment = $($(object).parent().parent().parent().find('textarea'))[0].value;
    $($(object).parent().parent().parent().find('textarea'))[0].value = '';
    if (comment.length == 0) {
        $($(object).parent().parent().parent().find('.err_msg')).css('display', 'block');
    }
    else {
        $.ajax({
            url: '/comment/' + comment_id + '/edit',
            type: 'POST',
            data: { 'comment' : comment },
            success: function (data) {
                // try find error message
                try {
                    if (JSON.parse(data)['err_msg_critical'] != undefined) {
                        console.log("Can't edit comment. Method is not allowed for the user.");
                    }
                    else if (JSON.parse(data)['err_msg'] != undefined) {
                        $($(object).parent().parent().parent().find('.err_msg')).css('display', 'block');
                    }
                }
                // if there is no error messages, insert recieved data where needed
                catch (e) {
                    $(data).insertAfter($($(object).parent().parent().parent().parent()));
                    $($(object).parent().parent().parent().parent()).remove();
                }
            },
            error: function (data) {
                console.log("Something went wrong...");
            },
        });
    }
};

// function processing comment deletion
function deleteComment(object, comment_id){
    $.ajax({
        url: '/comment/' + comment_id + '/delete',
        type: 'POST',
        data: { 'comment_id' : comment_id },
        success: function (data) {
            // try find error message
            if (JSON.parse(data)['err_msg_critical'] != undefined) {
                console.log("Can't delete comment. Method is not allowed for the user.");
            }
            else if (JSON.parse(data)['err_msg'] != undefined) {
                $($(object).parent().parent().find('.err_msg')).css('display', 'block');
            }
            // if there is no error messages, delete comment
            else {
                $(object).parent().parent().remove();
            }
        },
        error: function (data) {
            console.log("Something went wrong...");
        },
    });
};

